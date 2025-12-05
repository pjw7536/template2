import logoPng from '../images/logo.png';

const LogoVector = (props) => {
  const { alt = 'Logo', ...imgProps } = props;

  return (
    <img
      src={logoPng}
      alt={alt}
      {...imgProps}
    />
  );
};

export default LogoVector
