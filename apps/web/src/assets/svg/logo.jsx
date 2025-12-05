import logoPng from '../images/logo.png';

const Logo = (props) => {
  const { alt = 'Logo', ...imgProps } = props;

  return (
    <img
      src={logoPng}
      alt={alt}
      {...imgProps}
    />
  );
};

export default Logo
